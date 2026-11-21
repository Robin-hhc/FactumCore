/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04568(unsigned int count)
{
    const unsigned int limit = 225u;
    return count > limit ? limit : count;
}
