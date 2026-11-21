/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_07346(unsigned int count)
{
    const unsigned int limit = 141u;
    return count > limit ? limit : count;
}
