/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02261(unsigned int count)
{
    const unsigned int limit = 99u;
    return count > limit ? limit : count;
}
