/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_00538(unsigned int count)
{
    const unsigned int limit = 190u;
    return count > limit ? limit : count;
}
