/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02641(unsigned int count)
{
    const unsigned int limit = 85u;
    return count > limit ? limit : count;
}
