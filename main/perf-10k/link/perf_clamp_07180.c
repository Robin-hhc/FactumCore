/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_07180(unsigned int count)
{
    const unsigned int limit = 58u;
    return count > limit ? limit : count;
}
