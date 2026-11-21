/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_07261(unsigned int count)
{
    const unsigned int limit = 190u;
    return count > limit ? limit : count;
}
