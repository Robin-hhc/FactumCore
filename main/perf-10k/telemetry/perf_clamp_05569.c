/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_05569(unsigned int count)
{
    const unsigned int limit = 61u;
    return count > limit ? limit : count;
}
